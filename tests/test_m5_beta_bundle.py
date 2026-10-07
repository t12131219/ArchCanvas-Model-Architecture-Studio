from __future__ import annotations

import io
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.m5_beta_bundle import BUNDLE_MANIFEST, activate, install, pack, read_bundle, source_paths, verify


ROOT = Path(__file__).resolve().parents[1]


def write_self_consistent_archive(path: Path, manifest: dict, contents: dict[str, bytes]) -> None:
    """Build a counterexample whose outer byte inventory is self-consistent."""
    manifest["files"] = [{"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                         for name, data in contents.items()]
    manifest["releaseManifestSha256"] = hashlib.sha256(contents["docs/evidence/m5-beta-release-manifest.json"]).hexdigest()
    with tarfile.open(path, "w:gz") as archive:
        for name, data in {**contents, BUNDLE_MANIFEST: json.dumps(manifest).encode()}.items():
            member = tarfile.TarInfo(f"archcanvas-{manifest['version']}/{name}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


class M5BetaBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-m5-bundle-tests-")
        cls.work = Path(cls.temporary.name)
        cls.bundle = cls.work / "archcanvas-0.1.0-beta.1.tar.gz"
        cls.package = pack(ROOT, cls.bundle)
        cls.version = cls.package["version"]
        cls.next_version = cls.version.rsplit(".", 1)[0] + "." + str(int(cls.version.rsplit(".", 1)[1]) + 1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_inventory_covers_runtime_studio_skill_schema_and_locks(self) -> None:
        manifest, contents = read_bundle(self.bundle)
        self.assertEqual(manifest["hostE2E"], {"codex": "not-tested", "claude-code": "not-tested", "deepseek-harness": "not-tested"})
        for name in ("src/archcanvas_cli/__main__.py", "studio/dist/index.html", "fixtures/transformer/model.py",
                     "skills/archcanvas/SKILL.md", "schemas/canvas-document.schema.json", "requirements.lock",
                     "requirements-runtime.lock", "THIRD_PARTY_NOTICES.md"):
            self.assertIn(name, contents)
        self.assertFalse(any(".venv" in name or "__pycache__" in name or "node_modules" in name for name in contents))

    def test_independent_extraction_analyzes_three_models_without_execution(self) -> None:
        result = verify(self.bundle, self.work / "independent-release")
        self.assertEqual(result["analysis"]["status"], "passed")
        self.assertEqual(len(result["analysis"]["fixtures"]), 3)
        self.assertFalse(result["analysis"]["modelExecution"])

    def test_install_upgrade_and_rollback_keep_version_bytes(self) -> None:
        prefix = self.work / "upgrade-prefix"
        first = install(self.bundle, prefix, True)
        second_bundle = self.work / f"archcanvas-{self.next_version}.tar.gz"
        # The newer package is explicitly a synthetic test source tree.
        candidate = self.work / "synthetic-next-source"
        candidate.mkdir()
        for source in source_paths(ROOT):
            destination = candidate / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        metadata_path = candidate / "docs/evidence/m5-beta-release-manifest.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["releaseVersion"] = self.next_version
        metadata["releaseId"] = f"archcanvas-m5-beta-{self.next_version}"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        pack(candidate, second_bundle)
        verify(second_bundle, self.work / "synthetic-next-extraction")
        install(second_bundle, prefix, True)
        self.assertEqual((prefix / "current").resolve(), prefix / "releases" / self.next_version)
        result = activate(prefix, self.version)
        self.assertEqual(result["previousVersion"], self.next_version)
        self.assertEqual((prefix / "current").resolve(), Path(first["installedDirectory"]))

    def test_existing_bundle_is_never_overwritten(self) -> None:
        with self.assertRaisesRegex(ValueError, "existing bundle"):
            pack(ROOT, self.bundle)

    def test_version_override_cannot_relabel_release_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "must match"):
            pack(ROOT, self.work / "forged-next.tar.gz", self.next_version)

    def test_archive_traversal_is_rejected(self) -> None:
        malicious = self.work / "traversal.tar.gz"
        with tarfile.open(malicious, "w:gz") as archive:
            member = tarfile.TarInfo("archcanvas-0.1.0-beta.1/../../escape")
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
        with self.assertRaisesRegex(ValueError, "unsafe archive"):
            read_bundle(malicious)

    def test_archive_symlink_is_rejected(self) -> None:
        malicious = self.work / "symlink.tar.gz"
        with tarfile.open(malicious, "w:gz") as archive:
            member = tarfile.TarInfo("archcanvas-0.1.0-beta.1/src/link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/tmp"
            archive.addfile(member)
        with self.assertRaisesRegex(ValueError, "non-regular"):
            read_bundle(malicious)

    def test_modified_installed_file_blocks_activation(self) -> None:
        prefix = self.work / "modified-prefix"
        result = install(self.bundle, prefix)
        target = Path(result["installedDirectory"]) / "src/archcanvas_cli/__init__.py"
        target.write_text("# changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            activate(prefix, self.version)
        self.assertFalse((prefix / "current").exists())

    def test_activation_does_not_replace_user_current_directory(self) -> None:
        prefix = self.work / "user-content-prefix"
        install(self.bundle, prefix)
        (prefix / "current").mkdir()
        (prefix / "current/note.txt").write_text("user content", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "user content"):
            activate(prefix, self.version)
        self.assertEqual((prefix / "current/note.txt").read_text(), "user content")

    def test_temporary_state_symlink_cannot_write_outside_prefix(self) -> None:
        prefix = self.work / "temporary-state-symlink-prefix"
        install(self.bundle, prefix)
        victim = self.work / "user-file.txt"
        victim.write_text("user content", encoding="utf-8")
        (prefix / ".activation-next.json").symlink_to(victim)
        with self.assertRaisesRegex(ValueError, "stale .activation-next"):
            activate(prefix, self.version)
        self.assertEqual(victim.read_text(), "user content")
        self.assertFalse((prefix / "current").exists())

    def test_unregistered_current_symlink_is_preserved(self) -> None:
        prefix = self.work / "unregistered-pointer-prefix"
        install(self.bundle, prefix)
        (prefix / "current").symlink_to(self.work, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "not registered"):
            activate(prefix, self.version)
        self.assertEqual((prefix / "current").resolve(), self.work)

    def test_unrecognized_activation_receipt_is_preserved(self) -> None:
        prefix = self.work / "user-state-prefix"
        install(self.bundle, prefix)
        (prefix / "activation.json").write_text('{"user":"content"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not a recognized"):
            activate(prefix, self.version)
        self.assertEqual((prefix / "activation.json").read_text(), '{"user":"content"}')

    def test_false_installed_host_claim_blocks_activation(self) -> None:
        prefix = self.work / "forged-host-prefix"
        installed = install(self.bundle, prefix)
        path = Path(installed["installedDirectory"]) / BUNDLE_MANIFEST
        manifest = json.loads(path.read_text())
        manifest["hostE2E"]["codex"] = "passed"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cannot certify"):
            activate(prefix, self.version)

    def test_frozen_beta1_remains_verifiable_and_installable(self) -> None:
        frozen = ROOT / ".archcanvas/releases/archcanvas-0.1.0-beta.1.tar.gz"
        if not frozen.exists():
            self.skipTest("Historical beta.1 archive is not distributed; supply it in the checkout for baseline compatibility testing.")
        self.assertEqual(hashlib.sha256(frozen.read_bytes()).hexdigest(),
                         "2c44459c195540fd3ac99a0fa7f52583090d85eae47b26fea4a64d1da85ff9ff")
        manifest, contents = read_bundle(frozen)
        self.assertEqual(manifest["version"], "0.1.0-beta.1")
        self.assertNotIn("scripts/m5_host_install.py", contents)
        installed = install(frozen, self.work / "frozen-beta1-prefix", True)
        self.assertEqual(installed["activation"]["currentVersion"], "0.1.0-beta.1")

    def test_new_candidate_cannot_omit_its_host_installer_even_with_matching_inventory(self) -> None:
        manifest, contents = read_bundle(self.bundle)
        release = json.loads(contents["docs/evidence/m5-beta-release-manifest.json"])
        release["releaseVersion"] = "0.1.0-beta.2"
        release["releaseId"] = "archcanvas-m5-beta-0.1.0-beta.2"
        contents["docs/evidence/m5-beta-release-manifest.json"] = json.dumps(release).encode()
        contents.pop("scripts/m5_host_install.py")
        manifest["version"] = manifest["releaseMetadataVersion"] = "0.1.0-beta.2"
        malformed = self.work / "new-candidate-missing-installer.tar.gz"
        write_self_consistent_archive(malformed, manifest, contents)
        with self.assertRaisesRegex(ValueError, "version-required.*m5_host_install"):
            read_bundle(malformed)

    def test_file_directory_collision_is_rejected_before_installation(self) -> None:
        manifest, contents = read_bundle(self.bundle)
        contents.update({"foo": b"file", "foo/bar": b"child"})
        malformed = self.work / "prefix-collision.tar.gz"
        write_self_consistent_archive(malformed, manifest, contents)
        prefix = self.work / "prefix-collision-install"
        with self.assertRaisesRegex(ValueError, "prefix collision"):
            install(malformed, prefix)
        self.assertFalse(prefix.exists())

    def test_invalid_inner_metadata_is_rejected_before_installation(self) -> None:
        manifest, contents = read_bundle(self.bundle)
        release = json.loads(contents["docs/evidence/m5-beta-release-manifest.json"])
        release["build"]["runtimeSource"] = "failed-prototype"
        contents["docs/evidence/m5-beta-release-manifest.json"] = json.dumps(release).encode()
        malformed = self.work / "invalid-inner-metadata.tar.gz"
        write_self_consistent_archive(malformed, manifest, contents)
        prefix = self.work / "invalid-inner-install"
        with self.assertRaisesRegex(ValueError, "release schema invalid"):
            install(malformed, prefix)
        self.assertFalse(prefix.exists())

    def test_failed_staging_keeps_other_files_and_leaves_no_version(self) -> None:
        prefix = self.work / "staging-failure-prefix"
        releases = prefix / "releases"
        releases.mkdir(parents=True)
        (releases / "user.txt").write_text("preserve", encoding="utf-8")
        with patch("scripts.m5_beta_bundle.verify_directory", side_effect=ValueError("injected validation failure")):
            with self.assertRaisesRegex(ValueError, "injected validation failure"):
                install(self.bundle, prefix)
        self.assertEqual(sorted(path.name for path in releases.iterdir()), ["user.txt"])
        self.assertEqual((releases / "user.txt").read_text(), "preserve")

    def test_malformed_inner_schema_returns_a_validation_failure(self) -> None:
        manifest, contents = read_bundle(self.bundle)
        contents["schemas/m5-beta-release.schema.json"] = b'{"type": []}'
        malformed = self.work / "malformed-schema.tar.gz"
        write_self_consistent_archive(malformed, manifest, contents)
        with self.assertRaisesRegex(ValueError, "release schema invalid"):
            read_bundle(malformed)


if __name__ == "__main__":
    unittest.main()
