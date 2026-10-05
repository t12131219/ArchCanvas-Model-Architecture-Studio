"""Real CLI execution/receipt exit semantics with an explicit formal runtime."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m3_runtime_oracle import INPUT_SPEC, SOURCE

ROOT = Path(__file__).resolve().parents[1]


class M3CLIRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="archcanvas-runtime-cli-")
        self.root = Path(self.directory.name)
        (self.root / "model.py").write_text(SOURCE)
        self.spec_path = self.root / "input-spec.json"
        self.spec_path.write_text(json.dumps(INPUT_SPEC))

    def tearDown(self):
        self.directory.cleanup()

    def command(self, *extra):
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        return subprocess.run([sys.executable, "-B", "-m", "archcanvas_cli", "runtime", "--root", str(self.root), "--entry", "model:CrossAttention", "--input-spec", str(self.spec_path), "--interpreter", str(ROOT / ".venv-runtime/bin/python"), "--dependency-lock", str(ROOT / "requirements-runtime.lock"), *extra], capture_output=True, text=True, env=environment, timeout=30)

    def assert_available(self, receipt):
        if receipt["status"] == "unavailable":
            if os.environ.get("ARCHCANVAS_REQUIRE_RUNTIME") == "1":
                self.fail(str(receipt))
            self.skipTest(receipt.get("reason", "Actual sandbox unavailable"))

    def test_explicit_cli_profile_creates_a_bound_receipt_and_keeps_original_source(self):
        output = self.root / "receipt.json"
        before = (self.root / "model.py").read_bytes()
        result = self.command("--output", str(output))
        self.assertTrue(output.is_file(), result.stderr)
        receipt = json.loads(output.read_text())
        self.assert_available(receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(receipt["status"], "passed", receipt.get("reason"))
        self.assertEqual(receipt["profile"], "structural-verified")
        self.assertTrue(receipt["environmentDigest"])
        self.assertTrue(receipt["manifest"]["isolation"]["available"])
        self.assertEqual([mode["mode"] for mode in receipt["observation"]["modes"]], ["eval", "train"])
        self.assertEqual((self.root / "model.py").read_bytes(), before)

    def test_failed_forward_returns_nonzero_and_a_failed_json_receipt(self):
        invalid = copy.deepcopy(INPUT_SPEC)
        invalid["inputs"]["mask"]["shape"] = [3, 4]
        self.spec_path.write_text(json.dumps(invalid))
        result = self.command()
        receipt = json.loads(result.stdout)
        self.assert_available(receipt)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse(receipt["runtimeVerified"])


if __name__ == "__main__":
    unittest.main()
