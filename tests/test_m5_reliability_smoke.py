"""Independent installed-service refusals and persistence, without approval."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.m5_beta_bundle import pack, stage_current_candidate, verify
from scripts.m5_host_install import HOST_TARGETS, install_host
from scripts.m5_reliability_smoke import FailureClient, run_reliability


ROOT = Path(__file__).resolve().parents[1]


class InstalledReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-m5-reliability-tests-")
        cls.work = Path(cls.temporary.name)
        cls.release = cls.work / "release"
        bundle = cls.work / "current-candidate.tar.gz"
        source = stage_current_candidate(ROOT, cls.work / "current-source", "0.1.0-beta.3")
        pack(source, bundle)
        verify(bundle, cls.release, analyze=False)
        workspace = cls.work / "workspace"
        workspace.mkdir()
        install_host(cls.release, workspace, "codex")
        cls.skill = workspace / HOST_TARGETS["codex"]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_existing_evidence_is_preserved_without_spawning_a_process(self):
        output = self.work / "existing"
        output.mkdir()
        marker = output / "receipt.json"
        marker.write_bytes(b"earlier independent evidence\n")
        with patch("scripts.m5_reliability_smoke.LocalService") as service:
            with self.assertRaisesRegex(ValueError, "new explicit"):
                run_reliability(self.skill, output)
            service.assert_not_called()
        self.assertEqual(marker.read_bytes(), b"earlier independent evidence\n")

    def test_evidence_cannot_contaminate_installed_inventory(self):
        with patch("scripts.m5_reliability_smoke.LocalService") as service:
            with self.assertRaisesRegex(ValueError, "outside installed"):
                run_reliability(self.skill, self.skill / "new-evidence")
            service.assert_not_called()
        self.assertFalse((self.skill / "new-evidence").exists())

    def test_client_does_not_count_wrong_status_or_nonobject_response_as_pass(self):
        client = FailureClient("http://127.0.0.1:8765")
        with patch.object(client, "request", return_value=(200, b'{"error":"failed"}', {})):
            with self.assertRaisesRegex(ValueError, "got 200"):
                client.expect("/api/authoring/validate", "POST", {}, 400)
        with patch.object(client, "request", return_value=(400, b'[]', {})):
            with self.assertRaisesRegex(ValueError, "object"):
                client.expect("/api/authoring/validate", "POST", {}, 400)

    def test_actual_installed_service_refuses_edits_and_recovers_after_restart(self):
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
        except PermissionError:
            self.skipTest("Loopback socket bind unavailable in this sandbox; run on permitted local host.")
        result = run_reliability(self.skill, self.work / "actual", Path(sys.executable))
        self.assertEqual(result["status"], "passed", result.get("error"))
        self.assertEqual([item["check"] for item in result["checks"]], [
            "wrong-port-direction", "shape-conflict-save", "draft-storage-conflict",
            "canvas-storage-conflict", "invalid-export-format", "stale-semantic-binding",
            "unapproved-source-commit", "restart-session-rotation-and-exact-persistence",
            "installed-inventory-and-fixtures-unchanged"])
        self.assertTrue(all(item["stopped"] for item in result["serviceLifecycles"]))
        self.assertEqual(len(result["serviceLifecycles"]), 2)
        self.assertFalse(result["modelExecution"])
        self.assertFalse(result["humanApproval"])
        self.assertFalse(result["sourceCommitted"])
        self.assertEqual(result["hostE2E"], "not-tested")
        # Session tokens are never written into diagnostic evidence.
        receipt = json.loads((self.work / "actual/receipt.json").read_text())
        self.assertNotIn("token", json.dumps(receipt).lower())


if __name__ == "__main__":
    unittest.main()
