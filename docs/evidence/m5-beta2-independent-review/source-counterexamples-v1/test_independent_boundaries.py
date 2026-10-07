"""Independent deliberate failures against the preserved M5 tool bytes.

Synthetic beta.2 packages are negative test data only, not released candidates.
No model source is imported, no approval is created and no HTTP service starts.
"""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import queue
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = Path(json.loads((HERE / "input-manifest.json").read_text())["formalProject"])
sys.path.insert(0, str(HERE / "inputs"))
from scripts import m5_beta_bundle as bundle
from scripts.m5_reliability_smoke import FailureClient, draft, exercise_refusals
from scripts.m5_host_smoke import LocalService


def archive(path, metadata, contents):
    metadata["files"] = [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                         for name, raw in contents.items()]
    metadata["releaseManifestSha256"] = hashlib.sha256(contents["docs/evidence/m5-beta-release-manifest.json"]).hexdigest()
    with tarfile.open(path, "w:gz") as result:
        for name, raw in {**contents, bundle.BUNDLE_MANIFEST: bundle.encode(metadata)}.items():
            member = tarfile.TarInfo(f"archcanvas-{metadata['version']}/{name}")
            member.size = len(raw)
            result.addfile(member, io.BytesIO(raw))


class ProbeClient:
    """Fake correct status responses while corrupting the intended invariant."""
    def __init__(self, state, mutate=False, wrong_diagnostic=False):
        self.state, self.mutate, self.wrong_diagnostic = state, mutate, wrong_diagnostic
        self.calls = 0

    def expect(self, path, method, body, status):
        self.calls += 1
        if self.calls == 1:
            return {"draft": draft(), "revision": 1}
        if self.mutate:
            (self.state / "refused-write.txt").write_text("This was falsely counted as a refused save.")
        return {"diagnostics": [{"code": "other" if self.wrong_diagnostic else "invalid_connection_endpoint", "edgeId": "e1"}]}


class IndependentBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-m5-independent-counters-")
        cls.work = Path(cls.temporary.name)
        cls.frozen = ROOT / ".archcanvas/releases/archcanvas-0.1.0-beta.1.tar.gz"
        cls.baseline_metadata, cls.baseline_contents = bundle.read_bundle(cls.frozen)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def candidate(self):
        metadata, contents = deepcopy(self.baseline_metadata), deepcopy(self.baseline_contents)
        release = json.loads(contents["docs/evidence/m5-beta-release-manifest.json"])
        release["releaseVersion"] = metadata["version"] = metadata["releaseMetadataVersion"] = "0.1.0-beta.2"
        release["releaseId"] = "archcanvas-m5-beta-0.1.0-beta.2"
        contents["docs/evidence/m5-beta-release-manifest.json"] = bundle.encode(release)
        # Only the declared mandatory tool paths matter for this parser probe;
        # these test-only bytes are never installed or executed as a tool.
        for name in bundle.LIFECYCLE_FILES:
            contents[name] = b"# independent parser probe; never executed\n"
        return metadata, contents

    def test_frozen_beta1_hash_and_old_required_inventory_remain_valid(self):
        self.assertEqual(hashlib.sha256(self.frozen.read_bytes()).hexdigest(),
                         "2c44459c195540fd3ac99a0fa7f52583090d85eae47b26fea4a64d1da85ff9ff")
        self.assertEqual(self.baseline_metadata["version"], "0.1.0-beta.1")
        self.assertNotIn("scripts/m5_host_install.py", self.baseline_contents)
        self.assertEqual(bundle.required_release_files("0.1.0-beta.1"), set(bundle.SOURCE_FILES))
        extracted = self.work / "legacy-release"
        bundle.verify(self.frozen, extracted, analyze=False)
        self.assertEqual(bundle.verify_directory(extracted)["version"], "0.1.0-beta.1")

    def test_self_consistent_new_archive_missing_lifecycle_tools_is_rejected(self):
        metadata, contents = self.candidate()
        valid = self.work / "synthetic-structurally-complete.tar.gz"
        archive(valid, deepcopy(metadata), contents)
        self.assertEqual(bundle.read_bundle(valid)[0]["version"], "0.1.0-beta.2")
        for index, missing in enumerate(bundle.LIFECYCLE_FILES):
            changed = deepcopy(contents)
            changed.pop(missing)
            malformed = self.work / f"missing-{index}.tar.gz"
            archive(malformed, deepcopy(metadata), changed)
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, "version-required"):
                bundle.read_bundle(malformed)

    def test_self_consistent_installed_directory_missing_new_tool_is_rejected(self):
        metadata, contents = self.candidate()
        valid = self.work / "synthetic-directory-complete.tar.gz"
        archive(valid, metadata, contents)
        metadata, contents = bundle.read_bundle(valid)
        complete = self.work / "new-release"
        bundle.write_directory(complete, metadata, contents)
        self.assertEqual(bundle.verify_directory(complete)["version"], "0.1.0-beta.2")
        missing = "scripts/m5_reliability_smoke.py"
        (complete / missing).unlink()
        metadata["files"] = [row for row in metadata["files"] if row["path"] != missing]
        (complete / bundle.BUNDLE_MANIFEST).write_bytes(bundle.encode(metadata))
        with self.assertRaisesRegex(ValueError, "version-required"):
            bundle.verify_directory(complete)

    def test_http_success_code_cannot_fake_expected_refusal(self):
        client = FailureClient("http://127.0.0.1:8765")
        with patch.object(client, "request", return_value=(200, b'{"error":"rejected"}', {})):
            with self.assertRaisesRegex(ValueError, "got 200"):
                client.expect("/api/authoring/validate", "POST", {}, 400)

    def test_http_error_code_without_expected_diagnostic_is_rejected(self):
        state, output = self.work / "diagnostic-state", self.work / "diagnostic-output"
        state.mkdir(); output.mkdir()
        with self.assertRaisesRegex(ValueError, "did not identify e1"):
            exercise_refusals(ProbeClient(state, wrong_diagnostic=True), state, output)

    def test_expected_refusal_that_mutates_persistence_is_rejected(self):
        state, output = self.work / "mutation-state", self.work / "mutation-output"
        state.mkdir(); output.mkdir()
        with self.assertRaisesRegex(ValueError, "changed persisted files"):
            exercise_refusals(ProbeClient(state, mutate=True), state, output)
        self.assertTrue((state / "refused-write.txt").is_file())

    def test_timeout_terminates_owned_child_and_preserves_unrelated_child(self):
        unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
        service = LocalService([sys.executable, "-c", "import time;time.sleep(30)"], self.work,
                               self.work / "timeout.stderr.txt", timeout=0.05)
        try:
            with self.assertRaises(queue.Empty):
                with service:
                    self.fail("silent child must not be accepted as a service")
            self.assertIsNotNone(service.process.poll())
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.terminate(); unrelated.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
