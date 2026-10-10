"""Independent lifecycle checks using a packed release as opaque input.

These tests never rewrite release metadata or execute a model. They check
byte preservation, discovery paths and rejection of changed/user content.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from scripts.m5_beta_bundle import pack, stage_current_candidate, verify
from scripts.m5_host_install import HOST_TARGETS, install_host, verify_install
from scripts.m5_host_uninstall import ARCHIVE_RECEIPT, _rename_no_replace, preview, restore, uninstall

ROOT = Path(__file__).resolve().parents[1]


def bytes_inventory(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class M5HostUninstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="archcanvas-m5-host-uninstall-")
        cls.work = Path(cls.temp.name)
        cls.bundle = cls.work / "candidate.tar.gz"
        source = stage_current_candidate(ROOT, cls.work / "current-source", "0.1.0-beta.3")
        pack(source, cls.bundle)
        cls.release = cls.work / "verified-candidate"
        verify(cls.bundle, cls.release, analyze=False)
        cls.bundle_digest = hashlib.sha256(cls.bundle.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        if hashlib.sha256(cls.bundle.read_bytes()).hexdigest() != cls.bundle_digest:
            raise AssertionError("opaque test input package changed")
        cls.temp.cleanup()

    def install(self, host="codex"):
        workspace = self.work / f"project-{uuid.uuid4().hex}"
        workspace.mkdir()
        install_host(self.release, workspace, host)
        return workspace, workspace / HOST_TARGETS[host]

    def archive(self, host="codex"):
        workspace, skill = self.install(host)
        token = preview(workspace, host)["installationSha256"]
        result = uninstall(workspace, host, token)
        return workspace, skill, Path(result["archiveDirectory"])

    def test_all_hosts_preview_archive_restore_preserve_every_byte_and_external_data(self):
        for host in HOST_TARGETS:
            with self.subTest(host=host):
                workspace, skill = self.install(host)
                external = workspace / "user-data"
                external.mkdir()
                (external / "document.json").write_bytes(b"user document\n")
                (workspace / "unrelated.txt").write_bytes(b"user file\n")
                before = bytes_inventory(skill)
                external_before = bytes_inventory(external)
                rendered = preview(workspace, host)
                self.assertFalse(rendered["writesPerformed"])
                result = uninstall(workspace, host, rendered["installationSha256"])
                archive = Path(result["archiveDirectory"])
                self.assertFalse(skill.exists())
                self.assertEqual(bytes_inventory(archive / "skill"), before)
                self.assertEqual(bytes_inventory(external), external_before)
                self.assertEqual((workspace / "unrelated.txt").read_bytes(), b"user file\n")
                self.assertEqual(result["hostE2E"], "not-tested")
                restored = restore(workspace, host, archive)
                self.assertEqual(bytes_inventory(skill), before)
                self.assertEqual(restored["installationSha256"], rendered["installationSha256"])
                self.assertEqual(verify_install(skill)["status"], "passed")
                self.assertEqual(json.loads((archive / ARCHIVE_RECEIPT).read_text())["status"], "restored")

    def test_unknown_directory_and_user_added_content_are_never_uninstalled(self):
        workspace = self.work / f"unknown-{uuid.uuid4().hex}"
        skill = workspace / HOST_TARGETS["codex"]
        skill.mkdir(parents=True)
        (skill / "user-note.txt").write_bytes(b"leave me\n")
        with self.assertRaises(ValueError):
            preview(workspace, "codex")
        self.assertEqual((skill / "user-note.txt").read_bytes(), b"leave me\n")
        workspace, skill = self.install()
        token = preview(workspace, "codex")["installationSha256"]
        (skill / "user-note.txt").write_bytes(b"leave me too\n")
        before = bytes_inventory(skill)
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            uninstall(workspace, "codex", token)
        self.assertEqual(bytes_inventory(skill), before)
        self.assertFalse((workspace / ".archcanvas/host-skill-archives").exists())

    def test_wrong_digest_and_tampered_skill_leave_discovery_intact(self):
        workspace, skill = self.install()
        before = bytes_inventory(skill)
        with self.assertRaisesRegex(ValueError, "changed since preview"):
            uninstall(workspace, "codex", "0" * 64)
        self.assertEqual(bytes_inventory(skill), before)
        token = preview(workspace, "codex")["installationSha256"]
        (skill / "SKILL.md").write_bytes(b"tampered\n")
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            uninstall(workspace, "codex", token)
        self.assertEqual((skill / "SKILL.md").read_bytes(), b"tampered\n")

    def test_archive_tampering_and_unknown_archive_files_are_preserved(self):
        workspace, skill, archive = self.archive()
        (archive / "user.txt").write_bytes(b"do not delete\n")
        with self.assertRaisesRegex(ValueError, "unexpected files"):
            restore(workspace, "codex", archive)
        self.assertFalse(skill.exists())
        self.assertEqual((archive / "user.txt").read_bytes(), b"do not delete\n")
        (archive / "user.txt").unlink()
        (archive / "skill/SKILL.md").write_bytes(b"tampered archive\n")
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            restore(workspace, "codex", archive)
        self.assertEqual((archive / "skill/SKILL.md").read_bytes(), b"tampered archive\n")

    def test_restore_existing_same_named_skill_or_empty_directory_never_overwrites(self):
        workspace, skill, archive = self.archive()
        skill.mkdir()
        with self.assertRaisesRegex(ValueError, "overwrite existing"):
            restore(workspace, "codex", archive)
        self.assertTrue(skill.is_dir())
        self.assertTrue((archive / "skill").is_dir())
        skill.rmdir()
        install_host(self.release, workspace, "codex")
        replacement = bytes_inventory(skill)
        with self.assertRaisesRegex(ValueError, "overwrite existing"):
            restore(workspace, "codex", archive)
        self.assertEqual(bytes_inventory(skill), replacement)

    def test_kernel_no_replace_protects_destination_created_after_validation(self):
        root = self.work / f"no-replace-{uuid.uuid4().hex}"
        root.mkdir()
        source, destination = root / "source", root / "destination"
        source.mkdir()
        (source / "installed.txt").write_bytes(b"source\n")
        destination.mkdir()  # empty directory must also be preserved
        with self.assertRaises(FileExistsError):
            _rename_no_replace(source, destination)
        self.assertEqual((source / "installed.txt").read_bytes(), b"source\n")
        self.assertTrue(destination.is_dir())

    def test_symlink_workspace_or_archive_root_are_rejected(self):
        workspace, skill = self.install()
        link = self.work / f"workspace-link-{uuid.uuid4().hex}"
        link.symlink_to(workspace, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            preview(link, "codex")
        token = preview(workspace, "codex")["installationSha256"]
        (workspace / ".archcanvas").mkdir()
        elsewhere = self.work / f"elsewhere-{uuid.uuid4().hex}"
        elsewhere.mkdir()
        (workspace / ".archcanvas/host-skill-archives").symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            uninstall(workspace, "codex", token)
        self.assertTrue(skill.is_dir())
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_failed_move_preserves_installed_tree_without_half_archive(self):
        workspace, skill = self.install()
        token = preview(workspace, "codex")["installationSha256"]
        before = bytes_inventory(skill)
        with patch("scripts.m5_host_uninstall._rename_no_replace", side_effect=OSError("injected unavailable move")):
            with self.assertRaisesRegex(OSError, "injected"):
                uninstall(workspace, "codex", token)
        self.assertEqual(bytes_inventory(skill), before)
        self.assertEqual(list((workspace / ".archcanvas/host-skill-archives").iterdir()), [])

    def test_host_mismatch_and_archive_replay_cannot_reassign_installation(self):
        workspace, skill, archive = self.archive("claude-code")
        with self.assertRaisesRegex(ValueError, "selected host"):
            restore(workspace, "codex", archive)
        self.assertFalse((workspace / HOST_TARGETS["codex"]).exists())
        restore(workspace, "claude-code", archive)
        with self.assertRaisesRegex(ValueError, "fields are invalid|unconsumed"):
            restore(workspace, "claude-code", archive)
        self.assertEqual(verify_install(skill)["host"], "claude-code")

    def test_whole_workspace_relocation_can_restore_without_old_path_dependency(self):
        workspace, skill, archive = self.archive()
        relative_archive = archive.relative_to(workspace)
        moved = self.work / f"relocated-{uuid.uuid4().hex}"
        shutil.move(workspace, moved)
        restored = restore(moved, "codex", moved / relative_archive)
        self.assertEqual(restored["skillDirectory"], str(moved / HOST_TARGETS["codex"]))
        self.assertEqual(verify_install(moved / HOST_TARGETS["codex"])["status"], "passed")

    def test_replacement_lifecycle_retains_both_archives_and_can_restore_prior_install(self):
        workspace, skill, original_archive = self.archive()
        original = bytes_inventory(original_archive / "skill")
        install_host(self.release, workspace, "codex")
        with self.assertRaisesRegex(ValueError, "overwrite existing"):
            restore(workspace, "codex", original_archive)
        replacement_token = preview(workspace, "codex")["installationSha256"]
        replacement_result = uninstall(workspace, "codex", replacement_token)
        replacement_archive = Path(replacement_result["archiveDirectory"])
        self.assertNotEqual(original_archive, replacement_archive)
        self.assertEqual(bytes_inventory(replacement_archive / "skill"), original)
        restore(workspace, "codex", original_archive)
        self.assertEqual(bytes_inventory(skill), original)
        self.assertTrue((replacement_archive / "skill").is_dir())

    def test_cli_requires_explicit_workspace_and_valid_token(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts/m5_host_uninstall.py"), "preview", "--host", "codex"], text=True, capture_output=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("--workspace --prefix is required", run.stderr)
        workspace, skill = self.install()
        run = subprocess.run([sys.executable, str(ROOT / "scripts/m5_host_uninstall.py"), "uninstall", "--host", "codex", "--workspace", str(workspace), "--expected-installation-sha256", "invalid"], text=True, capture_output=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("SHA256 from preview", run.stdout)
        self.assertTrue(skill.is_dir())


if __name__ == "__main__":
    unittest.main()
