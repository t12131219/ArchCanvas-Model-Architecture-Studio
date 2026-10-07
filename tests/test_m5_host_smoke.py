"""Independent failures exercise child ownership and safe provenance checks."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/m5_host_smoke.py"
SPEC = importlib.util.spec_from_file_location("m5_host_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class HostSmokeTests(unittest.TestCase):
    def test_service_rejects_remote_or_credential_urls(self):
        for value in ("http://example.com:8765", "http://127.0.0.1", "https://127.0.0.1:80",
                      "http://user@127.0.0.1:8000", "http://127.0.0.1:8000/path",
                      "http://127.0.0.1:8000/?secret=1", "http://127.0.0.1:0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                smoke.loopback_url(value)
        self.assertEqual(smoke.loopback_url("http://127.0.0.1:43851/"), "http://127.0.0.1:43851")

    def test_provenance_does_not_accept_independent_flag_alone(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "src").mkdir()
            module = root / "outside.py"
            module.write_text("")
            with self.assertRaisesRegex(ValueError, "outside"):
                smoke.verify_origins({"packageProvenance": {"independent": True, "projectRoot": str(root),
                                                            "modules": {"module": str(module)}}}, root)

    def test_timeout_stops_only_owned_child(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            service = smoke.LocalService([sys.executable, "-c", "import time; time.sleep(30)"],
                                         root, root / "stderr", timeout=0.05)
            try:
                with self.assertRaises(smoke.queue.Empty):
                    with service:
                        self.fail("Unexpected startup")
                self.assertIsNotNone(service.process.poll())
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_invalid_startup_stops_child_and_keeps_diagnostic(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            code = "import time,sys; print('not-json',flush=True); print('diagnostic',file=sys.stderr,flush=True); time.sleep(30)"
            service = smoke.LocalService([sys.executable, "-c", code], root, root / "stderr")
            with self.assertRaises(ValueError):
                with service:
                    self.fail("Unexpected startup")
            self.assertIsNotNone(service.process.poll())
            self.assertIn("diagnostic", (root / "stderr").read_text())


if __name__ == "__main__":
    unittest.main()
