from __future__ import annotations

import json
import unittest
import tempfile
import tarfile
from pathlib import Path

from scripts.check_m5_beta_release import validate
from scripts.m5_beta_bundle import stage_current_candidate


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/evidence/m5-beta-release-manifest.json"


class M5BetaReleaseTests(unittest.TestCase):
    def test_frozen_manifest_matches_frozen_release(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        archive = ROOT / ".archcanvas/releases/archcanvas-0.1.0-beta.2.tar.gz"
        with tempfile.TemporaryDirectory() as directory:
            frozen = Path(directory)
            # Read only the manifest-bound artifacts and schema from the trusted
            # frozen release; do not execute or extract arbitrary archive paths.
            with tarfile.open(archive, "r:gz") as bundle:
                for relative in {row["path"] for row in manifest["artifacts"]} | {"schemas/m5-beta-release.schema.json"}:
                    data = bundle.extractfile(f"archcanvas-0.1.0-beta.2/{relative}").read()
                    target = frozen / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            self.assertEqual(validate(manifest, frozen), [])
        self.assertEqual(manifest["gates"], {"m4": "partial", "m5": "in_progress"})

    def test_current_candidate_has_independent_valid_manifest(self) -> None:
        historical = MANIFEST.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            staged = stage_current_candidate(ROOT, Path(directory) / "candidate", "0.1.0-beta.4")
            current = json.loads((staged / "docs/evidence/m5-beta-release-manifest.json").read_text())
            self.assertEqual(validate(current, staged), [])
            self.assertEqual(current["releaseVersion"], "0.1.0-beta.4")
        self.assertEqual(MANIFEST.read_bytes(), historical)

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
