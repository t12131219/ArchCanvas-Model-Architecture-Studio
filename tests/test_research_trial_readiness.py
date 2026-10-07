import errno
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.research_trial_readiness import inspect_slots, package_snapshot, probe_port, relative_inside


class _FakeSocket:
    def __init__(self, error=None):
        self.error = error
        self.closed = False

    def bind(self, _address):
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


class ResearchTrialReadinessTests(unittest.TestCase):
    def test_probe_success_is_available_and_explicitly_not_running(self):
        sock = _FakeSocket()
        with patch("scripts.research_trial_readiness.socket.socket", return_value=sock):
            result = probe_port(43911)
        self.assertEqual(result["status"], "available")
        self.assertFalse(result["serviceRunning"])
        self.assertTrue(sock.closed)

    def test_probe_occupied_is_not_called_free(self):
        sock = _FakeSocket(OSError(errno.EADDRINUSE, "address already in use"))
        with patch("scripts.research_trial_readiness.socket.socket", return_value=sock):
            result = probe_port(43911)
        self.assertEqual(result["status"], "occupied")
        self.assertEqual(result["serviceRunning"], "unknown")
        self.assertTrue(sock.closed)

    def test_probe_permission_block_is_indeterminate(self):
        with patch("scripts.research_trial_readiness.socket.socket", side_effect=PermissionError(errno.EPERM, "operation not permitted")):
            result = probe_port(43911)
        self.assertEqual(result["status"], "probe-blocked")
        self.assertEqual(result["serviceRunning"], "unknown")

    def test_relative_inside_rejects_escape(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.assertTrue(relative_inside(root / "a" / "b", root))
            self.assertFalse(relative_inside(root / ".." / "outside", root))

    def test_snapshot_marks_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "plain.txt").write_text("x", encoding="utf-8")
            (root / "link.txt").symlink_to(root / "plain.txt")
            snapshot = package_snapshot(root)
        by_path = {entry["path"]: entry for entry in snapshot["files"]}
        self.assertEqual(by_path["plain.txt"]["bytes"], 1)
        self.assertTrue(by_path["link.txt"]["symlink"])

    def test_inspect_slots_requires_blank_unassigned_slots(self):
        with tempfile.TemporaryDirectory() as raw:
            package = Path(raw)
            slot = package / "slots" / "S01"
            (slot / "workspace" / "documents").mkdir(parents=True)
            (slot / "workspace" / "exports").mkdir()
            (slot / "incoming").mkdir()
            (slot / "review-template.json").write_text(json.dumps({
                "slotId": "S01", "participantCode": None, "status": "pending-independent-review"
            }), encoding="utf-8")
            baseline = slot / "workspace" / "documents" / "canvas.json"
            baseline.write_bytes(b"baseline")
            import hashlib
            manifest = {"slots": [{
                "slotId": "S01", "port": 43911, "assignment": "unassigned", "participantCode": None,
                "baselineEnvelope": {"path": "slots/S01/workspace/documents/canvas.json",
                                      "sha256": hashlib.sha256(b"baseline").hexdigest(), "bytes": 8}
            }]}
            result = inspect_slots(package, manifest)
        self.assertFalse(result["passed"])  # one slot is insufficient by protocol
        self.assertIn("manifest.slots must contain 3–5 slots", result["errors"])


if __name__ == "__main__":
    unittest.main()
