from __future__ import annotations

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
from scripts.m5_host_install import (
    BUNDLE_MANIFEST,
    CONTRACT_NAME,
    HOST_TARGETS,
    LAUNCHER,
    install_host,
    verify_install,
)


ROOT = Path(__file__).resolve().parents[1]


class M5HostInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="archcanvas-m5-host-install-")
        cls.work = Path(cls.temp.name)
        cls.release = cls.work / "independent-release"
        bundle = cls.work / "current-candidate.tar.gz"
        source = stage_current_candidate(ROOT, cls.work / "current-source", "0.1.0-beta.3")
        pack(source, bundle)
        verify(bundle, cls.release, analyze=False)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def install(self, host: str = "codex") -> tuple[Path, dict]:
        workspace = self.work / f"workspace-{host}-{uuid.uuid4().hex}"
        workspace.mkdir()
        result = install_host(self.release, workspace, host)
        return workspace / HOST_TARGETS[host], result

    def test_all_three_hosts_use_their_project_local_discovery_path(self) -> None:
        for host, relative in HOST_TARGETS.items():
            skill, result = self.install(host)
            self.assertTrue((skill / "SKILL.md").is_file())
            self.assertEqual(result["host"], host)
            self.assertEqual(result["scope"], "explicit-workspace")
            self.assertEqual(result["hostE2E"], "not-tested")

    def test_install_is_complete_and_embeds_a_single_runtime_skill(self) -> None:
        skill, result = self.install()
        contract = json.loads((skill / CONTRACT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(contract["skillDirectory"], str(skill))
        self.assertEqual(contract["runtimeRoot"], "runtime/release")
        self.assertEqual(contract["embeddedSkillExcluded"], "skills/archcanvas")
        self.assertFalse((skill / "runtime/release/skills/archcanvas").exists())
        self.assertTrue((skill / "SKILL.md").read_text(encoding="utf-8").startswith("---\n"))
        self.assertIn("Project-local installation", (skill / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue((skill / "runtime/release/src/archcanvas_cli/__main__.py").is_file())
        self.assertTrue((skill / "references/host-adapters.md").is_file())
        self.assertGreater(result["fileCount"], 100)
        self.assertEqual(verify_install(skill)["status"], "passed")

    def test_rewritten_document_links_are_local_and_survive_move(self) -> None:
        skill, _ = self.install()
        text = (skill / "references/visual-workflow.md").read_text(encoding="utf-8")
        self.assertIn("../runtime/release/docs/m5-beta-release.md", text)
        self.assertNotIn("../../../docs/m5-beta-release.md", text)
        moved = self.work / "moved" / "archcanvas"
        moved.parent.mkdir()
        shutil.move(skill, moved)
        checked = verify_install(moved)
        self.assertEqual(checked["skillDirectory"], str(moved.resolve()))
        command = [str(Path(checked["runtimeCommand"][0])), "-I", "-B", str(moved / LAUNCHER), "analyze", "--root", str(moved / "runtime/release/fixtures/mlp"), "--entry", "model:MLP"]
        run = subprocess.run(command, cwd=self.work, text=True, capture_output=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('"nodes"', run.stdout)

    def test_missing_historical_document_gets_a_local_explanation(self) -> None:
        skill, _ = self.install()
        missing = skill / "resources/unavailable/docs/evidence/m4-memory-continuity-current/checks-final-attempt-2/receipt.json"
        self.assertTrue(missing.is_file())
        self.assertIn("did not distribute", missing.read_text(encoding="utf-8"))

    def test_existing_skill_directory_is_never_overwritten(self) -> None:
        workspace = self.work / "collision-workspace"
        workspace.mkdir()
        target = workspace / ".agents/skills/archcanvas"
        target.mkdir(parents=True)
        note = target / "user-note.txt"
        note.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "overwrite existing"):
            install_host(self.release, workspace, "codex")
        self.assertEqual(note.read_text(encoding="utf-8"), "preserve")

    def test_symlink_release_and_workspace_are_rejected(self) -> None:
        workspace = self.work / "symlink-workspace"
        workspace.mkdir()
        release_link = self.work / "release-link"
        release_link.symlink_to(self.release, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            install_host(release_link, workspace, "codex")
        linked_workspace = self.work / "workspace-link"
        linked_workspace.symlink_to(workspace, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            install_host(self.release, linked_workspace, "codex")

    def test_symlink_inside_release_is_rejected_without_partial_target(self) -> None:
        release = self.work / "linked-release"
        shutil.copytree(self.release, release, symlinks=True)
        (release / "src/link").symlink_to(self.work, target_is_directory=True)
        workspace = self.work / "linked-release-workspace"
        workspace.mkdir()
        with self.assertRaisesRegex(ValueError, "symlink"):
            install_host(release, workspace, "codex")
        self.assertFalse((workspace / ".agents").exists())

    def test_corrupted_release_or_installed_bytes_is_rejected(self) -> None:
        release = self.work / "corrupt-release"
        shutil.copytree(self.release, release)
        (release / "src/archcanvas_cli/__init__.py").write_text("corrupt\n", encoding="utf-8")
        workspace = self.work / "corrupt-release-workspace"
        workspace.mkdir()
        with self.assertRaisesRegex(ValueError, "inventory mismatch|artifact|release"):
            install_host(release, workspace, "codex")
        skill, _ = self.install("claude-code")
        target = skill / "runtime/release/src/archcanvas_cli/__init__.py"
        target.write_text("corrupt\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            verify_install(skill)

    def test_partial_staging_is_cleaned_after_validation_failure(self) -> None:
        workspace = self.work / "failed-staging-workspace"
        workspace.mkdir()
        with patch("scripts.m5_host_install.verify_install", side_effect=ValueError("injected validation failure")):
            with self.assertRaisesRegex(ValueError, "injected validation"):
                install_host(self.release, workspace, "deepseek-harness")
        parent = workspace / ".dsh/skills"
        self.assertTrue(parent.is_dir())
        self.assertEqual(list(parent.iterdir()), [])

    def test_launcher_requires_external_state_for_service(self) -> None:
        skill, _ = self.install()
        run = subprocess.run([str(Path(verify_install(skill)["runtimeCommand"][0])), "-I", "-B", str(skill / LAUNCHER), "serve"], cwd=self.work, text=True, capture_output=True, check=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("explicit --data-dir", run.stderr + run.stdout)
        inside = subprocess.run([str(Path(verify_install(skill)["runtimeCommand"][0])), "-I", "-B", str(skill / LAUNCHER), "serve", "--data-dir", str(skill / "state")], cwd=self.work, text=True, capture_output=True, check=False)
        self.assertNotEqual(inside.returncode, 0)
        self.assertIn("outside", inside.stderr + inside.stdout)
        self.assertFalse((skill / "runtime/release/.archcanvas").exists())

    def test_contract_tampering_and_inventory_extra_file_are_rejected(self) -> None:
        skill, _ = self.install()
        (skill / "user-extra.txt").write_text("unexpected", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            verify_install(skill)
        (skill / "user-extra.txt").unlink()
        contract_path = skill / CONTRACT_NAME
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["hostE2E"] = "passed"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported host claim"):
            verify_install(skill)

    def test_prefix_alias_is_explicit_and_cli_rejects_missing_scope(self) -> None:
        workspace = self.work / "prefix-workspace"
        workspace.mkdir()
        # API uses the same explicit path semantics as --prefix.
        skill = workspace / ".agents/skills/archcanvas"
        install_host(self.release, workspace, "codex")
        self.assertTrue((skill / CONTRACT_NAME).is_file())
        run = subprocess.run([sys.executable, str(ROOT / "scripts/m5_host_install.py"), "install", "--release-dir", str(self.release), "--host", "codex"], text=True, capture_output=True, check=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("one of the arguments --workspace --prefix is required", run.stderr)


if __name__ == "__main__":
    unittest.main()
