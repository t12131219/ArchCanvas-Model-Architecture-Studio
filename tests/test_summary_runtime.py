"""Independent hand-authored CPU fixture and mandatory-isolation counterexamples."""
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from archcanvas_runtime.summary import normalize_summary_spec, observe_summary
from archcanvas_runtime import RuntimeProfileError, runtime_capabilities
from archcanvas_summary_semantic.schema import digest, validate_ir
from archcanvas_summary_semantic.source_runtime import build_index

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {'interpreter': str(ROOT / '.venv-runtime/bin/python'), 'dependencyLock': str(ROOT / 'requirements-runtime.lock')}
SOURCE = (ROOT / 'fixtures/summary_runtime/model.py').read_text()
SPEC = {'schema': 'semantic-inputs/1', 'constructor': {'width': 3}, 'modes': ['eval'], 'cases': [
    {'id': name, 'seed': 7, 'inputs': {'x': {'shape': [2, 3], 'dtype': 'float32', 'fill': 'ones'}, 'flag': {'value': flag}}}
    for name, flag in [('positive', True), ('negative', False)]]}


class SummaryRuntimeProfileTests(unittest.TestCase):
    def test_explicit_finite_json_and_original_summary_budgets_precede_execution(self):
        for change in [{'modes': []}, {'cases': []}, {'constructor': {'n': float('nan')}}, {'modes': ['unsupported']}, {'root': '/tmp'}]:
            with self.subTest(change=change), self.assertRaises(RuntimeProfileError):
                normalize_summary_spec({**SPEC, **change})
        for seed in [-1, 2**32]:
            bad = copy.deepcopy(SPEC); bad['cases'][0]['seed'] = seed
            with self.assertRaises(RuntimeProfileError): normalize_summary_spec(bad)
        value = normalize_summary_spec(SPEC); value['cases'][0]['inputs']['x']['shape'][0] = 99
        self.assertEqual(SPEC['cases'][0]['inputs']['x']['shape'], [2, 3])

    def test_missing_environment_or_cancelled_request_never_executes_a_model_or_fallback(self):
        with patch('archcanvas_runtime.summary._execute', side_effect=AssertionError('must not launch')):
            result = observe_summary({'model.py': SOURCE}, 'model:RuntimeFixture', SPEC)
            self.assertEqual(result['receipt']['status'], 'unavailable'); self.assertIsNone(result['document'])
            event = threading.Event(); event.set()
            result = observe_summary({'model.py': SOURCE}, 'model:RuntimeFixture', SPEC, {**CONFIG, 'cancelEvent': event})
            self.assertEqual(result['receipt']['reason'], 'cancelled'); self.assertFalse(result['receipt']['model_executed'])

    def test_source_generation_mismatch_and_http_paths_are_rejected_before_worker(self):
        with patch('archcanvas_runtime.summary._execute', side_effect=AssertionError('must not launch')):
            with self.assertRaises(RuntimeProfileError): observe_summary({'model.py': SOURCE}, 'model:RuntimeFixture', SPEC, CONFIG, 'wrong')
            with self.assertRaises(ValueError): observe_summary({'../model.py': SOURCE}, 'model:RuntimeFixture', SPEC, CONFIG)


class SummaryRuntimeActualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        capability = runtime_capabilities(CONFIG)
        if not capability['available']: raise unittest.SkipTest(capability.get('unavailableReason', 'Mandatory sandbox unavailable'))
        cls.result = observe_summary({'model.py': SOURCE}, 'model:RuntimeFixture', SPEC, CONFIG)
        if cls.result['receipt']['status'] != 'passed': raise AssertionError(cls.result['receipt'].get('reason'))

    def test_real_aten_tensor_producers_shared_calls_and_source_stack_match_handwritten_fixture(self):
        receipt = self.result['receipt']; self.assertTrue(receipt['runtimeVerified'])
        self.assertEqual(receipt['source_files'], {'model.py': SOURCE})
        self.assertEqual(receipt['binding']['source_generation'], {'model.py': digest(SOURCE.encode())})
        self.assertTrue(all(receipt['isolation']['formalProbe']['checks'].values()))
        self.assertTrue(receipt['source_unchanged']); self.assertEqual(receipt['device'], 'cpu')
        for run, last in zip(receipt['runs'], ['aten.add.Tensor', 'aten.sub.Tensor']):
            self.assertEqual([v['operator'] for v in run['events']], ['aten.t.default', 'aten.mm.default', 'aten.t.default', 'aten.mm.default', last])
            calls = [v for v in run['module_events'] if v['event'] == 'enter' and v['path'] == 'projection']
            self.assertEqual(len(calls), 2); self.assertNotEqual(calls[0]['id'], calls[1]['id'])
            self.assertEqual([v['source_stack'][0]['line'] for v in calls], [11, 12])
            self.assertTrue(all(v['source_stack'][0]['symbol'] == 'RuntimeFixture.forward' for v in calls))
            self.assertEqual(run['events'][1]['inputs'][0]['producer'], 'input:x')
            self.assertEqual(run['outputs'][0]['producer'], run['events'][-1]['id'])
            self.assertEqual(run['outputs'][0]['shape'], [2, 3]); self.assertTrue(run['replay']['matched'])
        self.assertEqual(receipt['trace_digest'], digest({k: v for k, v in receipt.items() if k != 'trace_digest'}))

    def test_real_unknown_calls_have_exact_invocation_regions_while_static_unknowns_and_coverage_survive(self):
        document = self.result['document']; self.assertTrue(validate_ir(document)['ok'])
        regions = document['source_runtime_index']['regions']; self.assertEqual(len(regions), 4)
        for region in regions:
            self.assertTrue(region['static_unknown_preserved']); self.assertEqual(region['inputs'][0]['argument_port'], 'arg:0')
        self.assertEqual({row['case'] for row in regions}, {'positive', 'negative'})
        self.assertFalse(document['coverage']['complete']); self.assertFalse(document['coverage']['claimed_for_arbitrary_inputs'])
        self.assertTrue(any(n['kind'] == 'opaque' and not n['id'].startswith('runtime:') for n in document['nodes']))
        self.assertEqual(document['coverage']['branches'][0]['observed'], ['false', 'true'])

    def test_failed_truncated_unreplayed_or_rebound_evidence_cannot_integrate_even_after_resealing(self):
        for change in [{'status': 'failed'}, {'truncated': True}, {'replay': {'matched': False}}]:
            document = copy.deepcopy(self.result['document']); document['runtime']['runs'][0].update(change)
            self.assertFalse(any(v['run'] == 0 for v in build_index(document)['regions']))
        document = copy.deepcopy(self.result['document']); document['runtime']['binding']['source_generation'] = {}
        self.assertFalse(build_index(document)['regions'])


class SummaryRuntimeExportTests(unittest.TestCase):
    def test_optional_torch_export_keeps_its_independent_capture_diagnostic_and_full_observation(self):
        capability = runtime_capabilities(CONFIG)
        if not capability['available']: self.skipTest(capability.get('unavailableReason', 'Mandatory sandbox unavailable'))
        spec = copy.deepcopy(SPEC); spec['cases'] = spec['cases'][:1]; spec['export'] = True
        result = observe_summary({'model.py': SOURCE}, 'model:RuntimeFixture', spec, CONFIG)
        self.assertEqual(result['receipt']['status'], 'passed', result['receipt'].get('reason'))
        run = result['receipt']['runs'][0]
        self.assertEqual([e['operator'] for e in run['events']], ['aten.t.default', 'aten.mm.default', 'aten.t.default', 'aten.mm.default', 'aten.add.Tensor'])
        capture = run['capture']; self.assertIn(capture['status'], ('captured', 'unsupported'))
        if capture['status'] == 'captured': self.assertTrue(any(n['op'] == 'placeholder' for n in capture['nodes']))
        else: self.assertTrue(capture['reason'])
        self.assertTrue(run['replay']['matched']); self.assertTrue(validate_ir(result['document'])['ok'])
        print('EXPORT_DIAGNOSTIC', json.dumps(capture)[:500])


if __name__ == '__main__': unittest.main()
