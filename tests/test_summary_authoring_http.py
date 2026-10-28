"""Exercise the real loopback/session boundary for Summary static modules."""
import unittest
import test_preview_backend as preview_http
from test_summary_authoring_bridge import SOURCE


class SummaryModuleHTTPTests(unittest.TestCase):
    setUp = preview_http.PreviewHTTPTests.setUp
    tearDown = preview_http.PreviewHTTPTests.tearDown
    request = preview_http.PreviewHTTPTests.request

    def test_module_endpoint_requires_session_and_same_origin_without_accepting_server_paths(self):
        path = "/api/preview/authoring/module"
        payload = {"source": SOURCE, "entry": "Block", "constructor": {"width": 12}}
        self.assertEqual(self.request(path, payload, token=False)[0], 403)
        self.assertEqual(self.request(path, payload, origin="http://untrusted.invalid")[0], 403)
        self.assertEqual(self.request(path, {**payload, "root": "/etc"})[0], 400)
        status, module = self.request(path, payload, origin=self.url)
        self.assertEqual(status, 200, module)
        self.assertEqual(module["schema"], "semantic-module/1")
        self.assertEqual(module["source"], SOURCE)
        self.assertFalse(module["analysis"]["executed"])
        self.assertFalse(module["analysis"]["boundary"]["sourceTransactionBinding"])
        self.assertEqual(list((self.root / "managed").glob("projects/*")), [])

    def test_bad_static_source_returns_client_error_and_followup_request_succeeds(self):
        path = "/api/preview/authoring/module"
        status, error = self.request(path, {"source": "class invalid:", "entry": "invalid"})
        self.assertEqual(status, 400, error)
        self.assertEqual(self.request(path, {"source": SOURCE, "entry": "Block"})[0], 200)


if __name__ == "__main__":
    unittest.main()
