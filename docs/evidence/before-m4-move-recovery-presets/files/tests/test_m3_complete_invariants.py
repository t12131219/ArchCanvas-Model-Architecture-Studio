"""Independent full-M3 reviewed MHA key rebind samples, all writes under /tmp."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from archcanvas_python import analyze_project
from archcanvas_transactions import TransactionError, TransactionManager
from m3_runtime_oracle import (EXPECTED_RELATIONS_AFTER, EXPECTED_RELATIONS_BEFORE,
                               EXPECTED_PARAMETER_FACTS, INPUT_SPEC, SOURCE, expected_source)


ROOT = Path(__file__).resolve().parents[1]


class M3CompleteInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from archcanvas_runtime import verify_structural
        cls.config = {
            'interpreter': os.environ.get('ARCHCANVAS_RUNTIME_PYTHON', str(ROOT / '.venv-runtime/bin/python')),
            'dependencyLock': os.environ.get('ARCHCANVAS_RUNTIME_LOCK', str(ROOT / 'requirements-runtime.lock')),
            'timeoutSeconds': 20, 'memoryMb': 4096, 'cpuSeconds': 20,
        }
        with tempfile.TemporaryDirectory(prefix='archcanvas-m3-profile-probe-', dir='/tmp') as directory:
            root = Path(directory)
            (root / 'model.py').write_text(SOURCE, encoding='utf-8')
            receipt = verify_structural(root, 'model:CrossAttention', copy.deepcopy(INPUT_SPEC), dict(cls.config))
        if receipt['status'] == 'unavailable':
            if os.environ.get('ARCHCANVAS_REQUIRE_RUNTIME') == '1':
                raise AssertionError(f'Required structural-verified runtime is unavailable: {receipt}')
            raise unittest.SkipTest(f'Formal runtime isolation unavailable: {receipt.get("reason", receipt.get("error", "unknown"))}')
        if receipt['status'] != 'passed':
            raise AssertionError(f'Independent MHA profile probe did not pass: {receipt}')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='archcanvas-m3-complete-oracle-', dir='/tmp')
        self.base = Path(self.directory.name)
        self.project = self.base / 'project'
        self.project.mkdir()
        self.model = self.project / 'model.py'
        self.model.write_bytes(SOURCE.encode())
        self.store = self.base / 'transactions'
        self.manager = TransactionManager(self.store)
        self.architecture = analyze_project(self.project, 'model:CrossAttention')

    def tearDown(self):
        self.directory.cleanup()

    def node(self, member):
        return next(n for n in self.architecture['nodes'] if n.get('instanceId', '').endswith('.' + member))

    def prepare(self, *, port='key', producer='key_activation', spec=None, config=None):
        target = self.node('attention')
        source = self.node(producer) if producer != 'q' else next(n for n in self.architecture['nodes'] if n['kind'] == 'Input' and n['label'] == 'q')
        return self.manager.prepare_rebind(
            root=self.project, entry='model:CrossAttention', nodeId=target['id'],
            portId=next(p['id'] for p in target['ports'] if p['name'] == port),
            producerNodeId=source['id'],
            producerPortId=next(p['id'] for p in source['ports'] if p['direction'] == 'out'),
            baseSourceDigest=self.architecture['sourceDigest'],
            inputSpec=copy.deepcopy(INPUT_SPEC if spec is None else spec),
            runtimeConfig=dict(self.config if config is None else config),
        )

    def assert_rejected(self, action):
        try:
            result = action()
        except TransactionError:
            return None
        self.assertIn(result['status'], {'Failed', 'Stale', 'RolledBack', 'ManualRecovery'})
        self.assertTrue(result.get('blockers') or result.get('recovery'))
        return result

    def relationships(self, graph):
        names = {node['id']: node.get('instanceId', '').rsplit('.', 1)[-1] if node.get('instanceId', '').count('.') >= 2 else node['label'] for node in graph['nodes']}
        ports = {port['id']: port['name'] for node in graph['nodes'] for port in node['ports']}
        return {(names[e['source']['nodeId']], ports[e['source']['portId']],
                 names[e['target']['nodeId']], ports[e['target']['portId']], e['role'])
                for e in graph['edges']}

    def test_mha_key_only_byte_relation_and_mandatory_execution_gate(self):
        self.assertEqual(self.relationships(self.architecture), EXPECTED_RELATIONS_BEFORE)
        before = self.model.read_bytes()
        record = self.prepare()
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        self.assertEqual(self.model.read_bytes(), before)
        self.assertEqual(next(g['status'] for g in record['gates'] if g['id'] == 'G6'), 'passed')
        self.assertEqual(record['intent']['kind'], 'RebindInput')
        self.assertEqual(record['intent']['before']['variable'], 'memory')
        self.assertEqual(record['intent']['after']['variable'], 'alternative')
        impact = record['checkpointImpact']
        self.assertTrue(impact['modelExecuted'])
        self.assertFalse(impact['checkpointLoaded'])
        self.assertEqual(impact['observedModes'], ['eval', 'train'])
        self.assertEqual(impact['coverage'], 'declared-input-samples-and-modes-only')
        self.assertEqual({item['key']: {key: item[key] for key in ('shape', 'dtype')}
                          for item in impact['entries']}, EXPECTED_PARAMETER_FACTS)
        self.assertEqual(impact['sharing'], {'sharedGroups': [], 'sharedStorageGroups': []})
        approved = self.manager.approve(record['id'], record['reviewDigest'])
        committed = self.manager.commit(record['id'], approved['approvalId'])
        self.assertEqual(committed['status'], 'Committed', committed.get('blockers'))
        self.assertEqual(self.model.read_bytes(), expected_source())
        observed = analyze_project(self.project, 'model:CrossAttention')
        self.assertEqual(self.relationships(observed), EXPECTED_RELATIONS_AFTER)
        self.assertEqual(observed, committed['committedArchitecture'])
        attention = next(n for n in observed['nodes'] if n['kind'] == 'MultiheadAttention')
        self.assertEqual(attention['parameters']['embed_dim'], 8)
        self.assertEqual(attention['parameters']['num_heads'], 2)
        self.assertEqual(attention['parameters']['dropout'], 0.2)
        self.assertFalse(any(e for e in observed['edges'] if e['source']['nodeId'] == attention['id'] and e['source']['portId'].endswith(':weights')))

    def test_key_value_length_mismatch_never_reaches_reviewready(self):
        result = self.assert_rejected(lambda: self.prepare(producer='q'))
        if result:
            self.assertNotEqual(next((g['status'] for g in result['gates'] if g['id'] == 'G6'), None), 'passed')
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_missing_runtime_configuration_cannot_downgrade_mha_to_static(self):
        target, source = self.node('attention'), self.node('key_activation')
        arguments = dict(root=self.project, entry='model:CrossAttention', nodeId=target['id'],
                         portId=next(p['id'] for p in target['ports'] if p['name'] == 'key'),
                         producerNodeId=source['id'], producerPortId=next(p['id'] for p in source['ports'] if p['direction'] == 'out'),
                         baseSourceDigest=self.architecture['sourceDigest'])
        self.assert_rejected(lambda: self.manager.prepare_rebind(**arguments))
        self.assert_rejected(lambda: self.manager.prepare_rebind(**arguments, inputSpec=copy.deepcopy(INPUT_SPEC)))
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_invalid_runtime_sample_cannot_be_approved(self):
        spec = copy.deepcopy(INPUT_SPEC)
        spec['inputs']['mask']['shape'] = [3, 4]
        receipt = self.assert_rejected(lambda: self.prepare(spec=spec))
        if receipt:
            with self.assertRaises(TransactionError):
                self.manager.approve(receipt['id'], receipt.get('reviewDigest'))
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_review_runtime_input_and_mode_tamper_invalidates_approval(self):
        record = self.prepare()
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        approved = self.manager.approve(record['id'], record['reviewDigest'])
        path = self.store / record['id'] / 'record.json'
        saved = json.loads(path.read_text(encoding='utf-8'))
        # Runtime intent spec is a mandatory public review fact. It must not
        # become a mutable sidecar after the concrete source diff was approved.
        self.assertIn('inputSpec', saved['intent'])
        saved['intent']['inputSpec']['seed'] = 99
        saved['intent']['inputSpec']['modes'] = ['eval']
        path.write_text(json.dumps(saved), encoding='utf-8')
        self.assert_rejected(lambda: self.manager.commit(record['id'], approved['approvalId']))
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_bound_dependency_lock_change_invalidates_commit(self):
        lock = self.base / 'runtime-dependency.lock'
        official = Path(self.config['dependencyLock'])
        lock.write_bytes(official.read_bytes())
        config = dict(self.config, dependencyLock=str(lock))
        record = self.prepare(config=config)
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        approved = self.manager.approve(record['id'], record['reviewDigest'])
        frozen = hashlib.sha256(lock.read_bytes()).hexdigest()
        lock.write_bytes(lock.read_bytes() + b'\n# later dependency manifest edit\n')
        self.assertNotEqual(hashlib.sha256(lock.read_bytes()).hexdigest(), frozen)
        self.assert_rejected(lambda: self.manager.commit(record['id'], approved['approvalId']))
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())

    def test_staging_value_role_change_cannot_borrow_verified_key_receipt(self):
        record = self.prepare()
        self.assertEqual(record['status'], 'ReviewReady', record.get('blockers'))
        approved = self.manager.approve(record['id'], record['reviewDigest'])
        staged = self.store / record['id'] / 'staged/model.py'
        staged.write_bytes(staged.read_bytes().replace(
            b'self.attention(q, alternative, memory,', b'self.attention(q, alternative, alternative,', 1))
        self.assert_rejected(lambda: self.manager.commit(record['id'], approved['approvalId']))
        self.assertEqual(self.model.read_bytes(), SOURCE.encode())


if __name__ == '__main__':
    unittest.main()
