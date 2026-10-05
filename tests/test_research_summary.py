"""Independent study denominators: abandoned researchers count, agents do not."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('research_summary', Path(__file__).resolve().parents[1] / 'scripts/summarize_research_tasks.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResearchSummaryTests(unittest.TestCase):
    def receipt(self, code='R01', kind='researcher', outcome='completed', seconds=120):
        started = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        checkpoints = []
        for i in range(5 if outcome == 'completed' else 2):
            elapsed = (i + 1) * seconds * 1000 / 6
            checkpoints.append({'task': i + 1, 'selfReportedComplete': True, 'elapsedMs': elapsed,
                'observation': {'sourceDigest': 'a' * 64, 'irDigest': 'b' * 64, 'visibleNodes': 20,
                    'visualRevision': str(i), 'at': (started + timedelta(milliseconds=elapsed)).isoformat(),
                    'expandedNodes': ['root'], 'exportLinks': []}})
        return {'schemaVersion': 1, 'protocol': 'archcanvas-m4-research-task/1', 'participantCode': code, 'participantKind': kind,
            'startedAt': started.isoformat(), 'finishedAt': (started + timedelta(seconds=seconds)).isoformat(),
            'outcome': outcome, 'checkpoints': checkpoints, 'notes': ''}

    def write(self, root, receipt):
        path = root / f'record-{len(list(root.iterdir()))}.json'
        path.write_text(json.dumps(receipt))
        return path

    def record(self, root, code, kind='researcher', outcome='completed', seconds=120):
        return self.write(root, self.receipt(code, kind, outcome, seconds))

    def assert_invalid(self, receipt, message):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(Path(directory), receipt)
            with self.assertRaisesRegex(ValueError, message):
                module.summarize([path])

    def test_abandoned_and_slow_researchers_stay_in_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [self.record(root, 'R01'), self.record(root, 'R02', seconds=200), self.record(root, 'R03', outcome='abandoned'), self.record(root, 'A01', kind='automation')]
            report = module.summarize(paths)
            self.assertEqual(report['researcherCount'], 3)
            self.assertEqual(report['within3MinutesCount'], 1)
            self.assertEqual(report['selfReportedCompletionRate'], 1 / 3)
            self.assertFalse(report['selfReportedRateTargetMet'])
            self.assertEqual(report['researchGate'], 'awaiting-independent-review')
            self.assertEqual(len(report['excluded']), 1)

    def test_duplicate_participant_and_unfinished_records_cannot_inflate_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                module.summarize([self.record(root, 'R01'), self.record(root, 'R01')])
            with self.assertRaisesRegex(ValueError, 'unfinished'):
                module.summarize([self.record(root, 'R02', outcome='running')])

    def test_only_automation_reports_no_researcher_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = module.summarize([self.record(root, 'A01', kind='automation')])
            self.assertEqual(report['researchGate'], 'not_run')
            self.assertIsNone(report['selfReportedCompletionRate'])
            self.assertFalse(report['sampleSizeTargetMet'])

    def test_codes_use_ui_syntax_and_normalized_duplicate_identity(self):
        for code in (' ', 'R 01', 'R01@example.com', 'r' * 41, 1):
            with self.subTest(code=code):
                self.assert_invalid(self.receipt(code), 'invalid participant code')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                module.summarize([self.record(root, 'R01'), self.record(root, ' R01 ')])
            report = module.summarize([self.record(root, ' R02 ')])
            self.assertEqual(report['participants'][0]['participantCode'], 'R02')

    def test_top_and_nested_objects_are_validated_before_reading_fields(self):
        for receipt in (None, [], 'receipt'):
            self.assert_invalid(receipt, 'expected an object')
        for value in (None, [], 1):
            with self.subTest(checkpoint=value):
                receipt = self.receipt()
                receipt['checkpoints'][0] = value
                self.assert_invalid(receipt, 'expected an object')
            with self.subTest(observation=value):
                receipt = self.receipt()
                receipt['checkpoints'][0]['observation'] = value
                self.assert_invalid(receipt, 'expected an object')
        receipt = self.receipt()
        receipt['environment'] = {'viewport': []}
        self.assert_invalid(receipt, 'viewport: expected an object')

    def test_digests_must_be_sha256_and_source_binding_cannot_change(self):
        for digest in ('source', 'x' * 64, '', None, 123):
            receipt = self.receipt()
            receipt['checkpoints'][0]['observation']['sourceDigest'] = digest
            self.assert_invalid(receipt, 'invalid source-bound scene digest')
        for key in ('sourceDigest', 'irDigest'):
            receipt = self.receipt()
            receipt['checkpoints'][1]['observation'][key] = 'c' * 64
            self.assert_invalid(receipt, 'binding changed')

    def test_nonfinite_negative_and_duplicate_checkpoint_times_are_rejected(self):
        for value in (None, -1, float('nan'), float('inf'), True, 10**400):
            receipt = self.receipt()
            receipt['checkpoints'][0]['elapsedMs'] = value
            self.assert_invalid(receipt, 'nonnegative finite')
        for value in (-1, float('nan'), float('inf'), True, '20'):
            receipt = self.receipt()
            receipt['checkpoints'][0]['observation']['visibleNodes'] = value
            self.assert_invalid(receipt, 'nonnegative integer')
        receipt = self.receipt()
        receipt['checkpoints'][1]['elapsedMs'] = receipt['checkpoints'][0]['elapsedMs']
        self.assert_invalid(receipt, 'strictly increase')
        self.assert_invalid(self.receipt(seconds=0), 'strictly increase')

    def test_short_positive_task_is_provisional_without_arbitrary_lower_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            report = module.summarize([self.record(Path(directory), 'R01', seconds=.006)])
            self.assertEqual(report['participants'][0]['durationMs'], 6)
            self.assertTrue(report['participants'][0]['selfReportedWithin3Minutes'])
            self.assertEqual(report['researchGate'], 'awaiting-independent-review')

    def test_naive_mixed_timezone_and_out_of_order_observation_are_rejected(self):
        receipt = self.receipt()
        receipt['startedAt'] = '2026-10-04T10:00:00'
        self.assert_invalid(receipt, 'include a timezone')
        receipt = self.receipt()
        receipt['finishedAt'] = '2026-10-04T18:02:00+08:00'
        self.assert_invalid(receipt, 'consistent timezone')
        receipt = self.receipt()
        receipt['checkpoints'][0]['observation']['at'] = '2026-10-04T18:00:20+08:00'
        self.assert_invalid(receipt, 'consistent timezone')
        receipt = self.receipt()
        receipt['checkpoints'][1]['observation']['at'] = receipt['startedAt']
        self.assert_invalid(receipt, 'outside the sequential task')
        receipt = self.receipt()
        receipt['finishedAt'] = '2026-10-04T09:59:00+00:00'
        self.assert_invalid(receipt, 'nonnegative finite')
