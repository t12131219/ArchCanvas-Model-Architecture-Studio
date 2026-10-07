from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.check_m5_beta_release import validate


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/evidence/m5-beta-release-manifest.json"


class M5BetaReleaseTests(unittest.TestCase):
    def test_current_manifest_is_valid_and_keeps_m4_partial(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(validate(manifest, ROOT), [])
        self.assertEqual(manifest["gates"], {"m4": "partial", "m5": "in_progress"})

    def test_hash_mismatch_is_rejected(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["artifacts"][0]["sha256"] = "0" * 64
        errors = validate(manifest, ROOT)
        self.assertTrue(any("hash mismatch" in error for error in errors))

    def test_missing_host_is_rejected(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["hostMatrix"] = manifest["hostMatrix"][:2]
        errors = validate(manifest, ROOT)
        self.assertTrue(any("hostMatrix" in error for error in errors))

    def test_prototype_runtime_is_rejected(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["build"]["runtimeSource"] = "ArchCanvas_Model Architecture Studio_Temp"
        errors = validate(manifest, ROOT)
        self.assertTrue(any("runtimeSource" in error for error in errors))

    def test_m4_completion_cannot_be_claimed_by_scaffold(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["gates"]["m4"] = "complete"
        self.assertTrue(any("gates.m4" in error for error in validate(manifest, ROOT)))

    def test_outside_project_artifact_is_rejected(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["artifacts"][0]["path"] = "../outside.js"
        self.assertTrue(any("artifacts[0].path" in error for error in validate(manifest, ROOT)))

    def test_false_host_certification_is_rejected(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["hostMatrix"][0]["e2e"] = "passed"
        self.assertTrue(any("hostMatrix[0].e2e" in error for error in validate(manifest, ROOT)))

    def test_false_release_claim_is_rejected(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["status"] = "released"
        self.assertTrue(any("status" in error for error in validate(manifest, ROOT)))

    def test_invalid_role_is_rejected_by_schema(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["artifacts"][0]["role"] = "unrecognized"
        self.assertTrue(any("artifacts[0].role" in error for error in validate(manifest, ROOT)))


if __name__ == "__main__":
    unittest.main()
