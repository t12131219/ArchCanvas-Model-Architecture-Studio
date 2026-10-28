"""Actual HTTP/session and async-cancel boundary; no model runs in these mocks."""
import threading
import time
import unittest
from unittest.mock import patch
import test_preview_backend as preview_http
from test_summary_runtime import SOURCE, SPEC


class SummaryRuntimeHTTPTests(unittest.TestCase):
    setUp = preview_http.PreviewHTTPTests.setUp
    tearDown = preview_http.PreviewHTTPTests.tearDown
    request = preview_http.PreviewHTTPTests.request

    def test_explicit_runtime_start_and_receipt_read_require_current_local_session_and_source_text(self):
        path = '/api/preview/runtime-jobs'; payload = {'files': {'model.py': SOURCE}, 'entry': 'model:RuntimeFixture', 'inputSpec': SPEC}
        with patch('archcanvas_runtime.summary.observe_summary', return_value={'receipt': {'status': 'unavailable', 'model_executed': False}, 'document': None, 'source': {}}) as observe:
            self.assertEqual(self.request(path, payload, token=False)[0], 403)
            self.assertEqual(self.request(path, payload, origin='http://untrusted.invalid')[0], 403)
            self.assertEqual(self.request(path, {**payload, 'root': '/etc'})[0], 400)
            self.assertEqual(self.request(path, {**payload, 'config': {'interpreter': '/usr/bin/python'}})[0], 400)
            status, job = self.request(path, payload, origin=self.url); self.assertEqual(status, 202, job)
            read = path + '/' + job['id']
            with self.assertRaises(ValueError): self.server.runtime_job('another-project', job['id'])
            self.assertEqual(self.request(read, token=False)[0], 403)
            self.assertEqual(self.request(read, origin='http://untrusted.invalid')[0], 403)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                status, state = self.request(read)
                if state['status'] != 'running': break
                time.sleep(.01)
            self.assertEqual(status, 200); self.assertEqual(state['result']['receipt']['status'], 'unavailable')
            self.assertNotIn('cancelEvent', state); self.assertEqual(observe.call_count, 1)
            self.assertEqual(list((self.root / 'managed').glob('projects/*')), [], 'observation never creates a source transaction')

    def test_cancel_targets_only_summary_jobs_and_serializes_against_formal_runtime_work(self):
        path = '/api/preview/runtime-jobs'; payload = {'files': {'model.py': SOURCE}, 'entry': 'model:RuntimeFixture', 'inputSpec': SPEC}
        started = threading.Event()
        def observe(files, entry, spec, config, source):
            started.set(); config['cancelEvent'].wait(3)
            return {'receipt': {'status': 'failed', 'reason': 'cancelled'}, 'document': None, 'source': {}}
        with patch('archcanvas_runtime.summary.observe_summary', side_effect=observe):
            status, job = self.request(path, payload); self.assertEqual(status, 202); self.assertTrue(started.wait(2))
            self.assertEqual(self.request(path, payload)[0], 400, 'no concurrent CPU job')
            read = path + '/' + job['id']
            self.assertEqual(self.request(read + '/cancel', {}, token=False)[0], 403)
            self.assertEqual(self.request(read + '/cancel', {'all': True})[0], 400)
            self.assertEqual(self.request(path + '/missing/cancel', {})[0], 400)
            self.assertEqual(self.request(read + '/cancel', {})[0], 200)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                _, state = self.request(read)
                if state['status'] != 'running': break
                time.sleep(.01)
            self.assertEqual(state['result']['receipt']['reason'], 'cancelled')
            self.assertIsNone(state['result']['document'])


if __name__ == '__main__': unittest.main()
